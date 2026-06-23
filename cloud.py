import boto3
import os
import json
import logging
from dotenv import load_dotenv

# Отключаем отладочные логи
logging.getLogger('boto3').setLevel(logging.WARNING)
logging.getLogger('botocore').setLevel(logging.WARNING)
logging.getLogger('urllib3').setLevel(logging.WARNING)

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
        try:
            self.client.upload_file(file_path, self
