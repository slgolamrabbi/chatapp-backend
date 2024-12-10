import os
import json
import hashlib
import boto3
from botocore.exceptions import ClientError

# Environment variables
WEBSOCKET_API_URL = os.environ['WEBSOCKET_API_URL']
TABLE_NAME = os.environ['TABLE_NAME']

# AWS clients
client = boto3.client('apigatewaymanagementapi', endpoint_url=WEBSOCKET_API_URL)
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(TABLE_NAME)

def generate_user_id(connection_id, user_name):
    """
    Generates a unique user ID by hashing the connection ID and user name.
    """
    hash_object = hashlib.sha256(f"{connection_id}{user_name}".encode('utf-8'))
    return f"user{hash_object.hexdigest()[:16]}"

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
    Lambda function handler.
    """
    # Extract connection ID and query parameters
    connection_id = event["requestContext"]["connectionId"]
    query_params = event.get('queryStringParameters', {})
    user_name = query_params.get('name')

    # Validate user input
    if not user_name:
        return {
            'statusCode': 400,
            'body': json.dumps('A name should be present')
        }

    # Generate a unique user ID and add it to DynamoDB
    random_user_id = generate_user_id(connection_id, user_name)
    entry = {"connection_id": connection_id, "random_user_id": random_user_id, "name": user_name}
    table.put_item(Item=entry)

    # Retrieve all online users
    online_users = get_online_users()

    # Broadcast the online users to all connections
    broadcast_online_users(connection_id, online_users)

    # Prepare response data
    user_data = {
        "online-users": [
            {"user_id": user['random_user_id'], "name": user['name']}
            for user in online_users
        ]
    }

    # Return the response
    return {
        'statusCode': 200,
        'body': json.dumps({
            'message': 'Connected to Websocket Api!',
            'userId': random_user_id,
            'data': user_data
        })
    }
