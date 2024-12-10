import os
import json
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

def delete_connection_items(connection_id):
    """
    Deletes all items associated with the given connection ID from the DynamoDB table.
    """
    try:
        response = table.query(
            KeyConditionExpression=Key('connection_id').eq(connection_id)
        )
        items = response.get('Items', [])
        
        for item in items:
            table.delete_item(
                Key={
                    'connection_id': item['connection_id'],
                    'random_user_id': item.get('random_user_id')
                }
            )
    except ClientError as e:
        print(f"Error deleting items for connection_id {connection_id}: {e}")

def get_online_users():
    """
    Retrieves all users currently in the DynamoDB table.
    """
    try:
        scan_response = table.scan()
        return scan_response.get('Items', [])
    except ClientError as e:
        print(f"Error scanning DynamoDB: {e}")
        return []

def broadcast_online_users(connection_id, online_users):
    """
    Sends a list of online users (user_id and name only) to all active connections except the sender.
    """
    user_data = {
        "online-users": [
            {"user_id": user['random_user_id'], "name": user['name']}
            for user in online_users
        ]
    }

    for user in online_users:
        if user['connection_id'] != connection_id:
            try:
                client.post_to_connection(
                    ConnectionId=user['connection_id'],
                    Data=json.dumps(user_data).encode('utf-8')
                )
            except ClientError as e:
                # Log and continue broadcasting to other connections
                print(f"Failed to send message to {user['connection_id']}: {e}")

def lambda_handler(event, context):
    """
    Lambda function handler for handling WebSocket disconnections.
    """
    connection_id = event["requestContext"]["connectionId"]

    # Delete the disconnected user's items from the table
    delete_connection_items(connection_id)

    # Get the updated list of online users
    online_users = get_online_users()

    # Broadcast the updated list to all other users
    broadcast_online_users(connection_id, online_users)

    return {
        'statusCode': 200,
        'body': json.dumps({
            'message': 'Disconnected from Websocket Api!'
        })
    }
