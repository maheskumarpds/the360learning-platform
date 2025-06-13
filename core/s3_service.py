import os
import boto3
import logging
from botocore.exceptions import ClientError
import uuid

from django.conf import settings

# Set up logging
logger = logging.getLogger(__name__)

# S3 Configuration
# These will be blank until user provides actual credentials
AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID', '')
AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY', '')
AWS_STORAGE_BUCKET_NAME = os.environ.get('AWS_STORAGE_BUCKET_NAME', '4clearning-recordings')
AWS_S3_REGION_NAME = os.environ.get('AWS_S3_REGION_NAME', 'us-east-1')
AWS_S3_SIGNATURE_VERSION = os.environ.get('AWS_S3_SIGNATURE_VERSION', 's3v4')

def get_s3_client():
    """
    Get an S3 client configured with our credentials
    
    Returns:
        boto3.client: The S3 client
    """
    return boto3.client(
        's3',
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
        region_name=AWS_S3_REGION_NAME
    )

def upload_file_to_s3(file_path, object_name=None, extra_args=None):
    """
    Upload a file to an S3 bucket
    
    Args:
        file_path (str): Path to the file to upload
        object_name (str, optional): S3 object name. If not specified, file_name from file_path is used
        extra_args (dict, optional): Additional arguments to pass to S3 client
        
    Returns:
        dict: Result with success status and uploaded file URL
    """
    # If S3 credentials are missing, return error
    if not AWS_ACCESS_KEY_ID or not AWS_SECRET_ACCESS_KEY:
        return {
            'success': False,
            'error': 'AWS credentials are not configured'
        }
    
    # If no object name provided, use the filename from file_path
    if object_name is None:
        object_name = os.path.basename(file_path)
    
    # Add a UUID to ensure uniqueness
    if '.' in object_name:
        base_name, extension = object_name.rsplit('.', 1)
        object_name = f"{base_name}_{uuid.uuid4().hex}.{extension}"
    else:
        object_name = f"{object_name}_{uuid.uuid4().hex}"
    
    # Default extra_args if none provided
    if extra_args is None:
        extra_args = {}
    
    # Create S3 client
    s3_client = get_s3_client()
    
    try:
        s3_client.upload_file(
            file_path, 
            AWS_STORAGE_BUCKET_NAME, 
            object_name,
            ExtraArgs=extra_args
        )
        
        # Generate the URL for the uploaded file
        file_url = f"https://{AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com/{object_name}"
        
        return {
            'success': True,
            'object_name': object_name,
            'file_url': file_url
        }
    except ClientError as e:
        logger.error(f"Error uploading file to S3: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }
    except Exception as e:
        logger.error(f"Unexpected error uploading to S3: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }

def delete_file_from_s3(object_name):
    """
    Delete a file from an S3 bucket
    
    Args:
        object_name (str): S3 object name to delete
        
    Returns:
        dict: Result with success status
    """
    # If S3 credentials are missing, return error
    if not AWS_ACCESS_KEY_ID or not AWS_SECRET_ACCESS_KEY:
        return {
            'success': False,
            'error': 'AWS credentials are not configured'
        }
    
    # Create S3 client
    s3_client = get_s3_client()
    
    try:
        s3_client.delete_object(
            Bucket=AWS_STORAGE_BUCKET_NAME,
            Key=object_name
        )
        
        return {
            'success': True,
            'message': f"Successfully deleted {object_name}"
        }
    except ClientError as e:
        logger.error(f"Error deleting file from S3: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }
    except Exception as e:
        logger.error(f"Unexpected error deleting from S3: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }

def create_presigned_url(object_name, expiration=3600):
    """
    Generate a presigned URL for an S3 object
    
    Args:
        object_name (str): S3 object name
        expiration (int): Time in seconds for the URL to remain valid
        
    Returns:
        str or None: Presigned URL if successful, None if error
    """
    # If S3 credentials are missing, return None
    if not AWS_ACCESS_KEY_ID or not AWS_SECRET_ACCESS_KEY:
        logger.error("AWS credentials are not configured")
        return None
    
    # Create S3 client
    s3_client = get_s3_client()
    
    try:
        response = s3_client.generate_presigned_url(
            'get_object',
            Params={
                'Bucket': AWS_STORAGE_BUCKET_NAME,
                'Key': object_name
            },
            ExpiresIn=expiration
        )
        
        return response
    except ClientError as e:
        logger.error(f"Error generating presigned URL: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error generating presigned URL: {str(e)}")
        return None

def list_s3_objects(prefix=None):
    """
    List objects in the S3 bucket
    
    Args:
        prefix (str, optional): Filter objects by prefix
        
    Returns:
        dict: Result with success status and list of objects
    """
    # If S3 credentials are missing, return error
    if not AWS_ACCESS_KEY_ID or not AWS_SECRET_ACCESS_KEY:
        return {
            'success': False,
            'error': 'AWS credentials are not configured'
        }
    
    # Create S3 client
    s3_client = get_s3_client()
    
    try:
        params = {'Bucket': AWS_STORAGE_BUCKET_NAME}
        if prefix:
            params['Prefix'] = prefix
        
        response = s3_client.list_objects_v2(**params)
        
        objects = []
        if 'Contents' in response:
            for obj in response['Contents']:
                objects.append({
                    'key': obj['Key'],
                    'size': obj['Size'],
                    'last_modified': obj['LastModified'].isoformat(),
                    'url': f"https://{AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com/{obj['Key']}"
                })
        
        return {
            'success': True,
            'objects': objects
        }
    except ClientError as e:
        logger.error(f"Error listing objects in S3: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }
    except Exception as e:
        logger.error(f"Unexpected error listing S3 objects: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }