import json
import os
import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

# Environment variables
WEBSOCKET_API_URL = os.environ['WEBSOCKET_API_URL']
TABLE_NAME = os.environ['TABLE_NAME']

# AWS clients
client = boto3.client('apigatewaymanagementapi', endpoint_url=WEBSOCKET_API_URL)
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(TABLE_NAME)

def get_connection_id_by_user_id(random_user_id):
    """
    Retrieves the connection ID for a given random_user_id using a DynamoDB GSI.
    """
    try:
        response = table.query(
            IndexName='random_user_id-index',  # GSI name
            KeyConditionExpression=Key('random_user_id').eq(random_user_id)
        )
        items = response.get('Items', [])
        return items[0]['connection_id'] if items else None
    except ClientError as e:
        print(f"Error querying connection ID by user ID: {e}")
        return None

def get_user_id_by_connection_id(connection_id):
    """
    Retrieves the random_user_id for a given connection ID from DynamoDB.
    """
    try:
        response = table.query(
            KeyConditionExpression=Key('connection_id').eq(connection_id)
        )
        items = response.get('Items', [])
        return items[0]['random_user_id'] if items else None
    except ClientError as e:
        print(f"Error querying user ID by connection ID: {e}")
        return None

def send_message_to_user(sender_connection_id, to_user, message):
    """
    Sends a message to a specific user identified by their random_user_id.
    """
    to_connection_id = get_connection_id_by_user_id(to_user)
    if to_connection_id and to_connection_id != sender_connection_id and message:
        message_to_send = {
            "message": message,
            "from": get_user_id_by_connection_id(sender_connection_id),
            "to": to_user
        }
        try:
            client.post_to_connection(
                ConnectionId=to_connection_id,
                Data=json.dumps(message_to_send).encode('utf-8')
            )
            return {"statusCode": 200}
        except ClientError as e:
            print(f"Failed to send message to {to_user} with connection ID {to_connection_id}: {e}")
    return {"statusCode": 400, "body": "Message could not be sent"}

def broadcast_message_to_all_except_sender(sender_connection_id, message, sender_user_id):
    """
    Broadcasts a message to all active connections except the sender.
    """
    try:
        scan_response = table.scan()
        items = scan_response.get('Items', [])
        for item in items:
            if item['connection_id'] != sender_connection_id:
                message_to_send = {
                    "message": message,
                    "from": sender_user_id
                }
                try:
                    client.post_to_connection(
                        ConnectionId=item['connection_id'],
                        Data=json.dumps(message_to_send).encode('utf-8')
                    )
                except ClientError as e:
                    print(f"Failed to send message to connection {item['connection_id']}: {e}")
    except ClientError as e:
        print(f"Error scanning DynamoDB for broadcasting: {e}")

def lambda_handler(event, context):
    """
    Lambda function to handle WebSocket messaging.
    """
    connection_id = event["requestContext"]["connectionId"]
    raw_body = event.get('body', '')
    body = json.loads(raw_body) if raw_body else {}

    message = body.get('message')
    to_user = body.get('to')

    # If a specific recipient is provided, send the message
    if to_user:
        return send_message_to_user(connection_id, to_user, message)

    # Otherwise, broadcast the message to all users except the sender
    sender_user_id = get_user_id_by_connection_id(connection_id)
    if message and sender_user_id:
        broadcast_message_to_all_except_sender(connection_id, message, sender_user_id)

    return {"statusCode": 200}
