# cloud.py
import boto3
import os
from dotenv import load_dotenv

load_dotenv()

class YandexCloudStorage:
    def __init__(self):
        self.bucket_name = os.environ.get('YANDEX_BUCKET', 'images-from-courier')
        self.endpoint = os.environ.get('YANDEX_ENDPOINT', 'https://storage.yandexcloud.net')
        self.client = boto3.client(
            service_name='s3',
            endpoint_url=self.endpoint,
            aws_access_key_id=os.environ.get('YANDEX_ACCESS_KEY'),
            aws_secret_access_key=os.environ.get('YANDEX_SECRET_KEY'),
        )
    
    def upload_file(self, file_path, object_name):
        """Загрузить файл в Yandex Cloud"""
        try:
            self.client.upload_file(file_path, self.bucket_name, object_name)
            url = f"https://storage.yandexcloud.net/{self.bucket_name}/{object_name}"
            return {'success': True, 'url': url}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def delete_file(self, object_name):
        """Удалить файл из Yandex Cloud"""
        try:
            self.client.delete_object(Bucket=self.bucket_name, Key=object_name)
            return {'success': True}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def get_metadata(self, object_name):
        """Получить информацию о файле"""
        try:
            response = self.client.head_object(
                Bucket=self.bucket_name,
                Key=object_name
            )
            return {
                'size': response.get('ContentLength'),
                'last_modified': response.get('LastModified'),
                'content_type': response.get('ContentType')
            }
        except Exception as e:
            return {'error': str(e)}
