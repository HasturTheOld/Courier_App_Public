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
            self.client.upload_file(file_path, self.bucket_name, object_name)
            url = f"https://storage.yandexcloud.net/{self.bucket_name}/{object_name}"
            return {'success': True, 'url': url, 'object_name': object_name}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def upload_metadata(self, object_name, metadata):
        """Загрузить метаданные как JSON файл рядом с фото"""
        try:
            json_key = object_name.rsplit('.', 1)[0] + '.json'
            json_data = json.dumps(metadata, ensure_ascii=False, indent=2)
            self.client.put_object(
                Bucket=self.bucket_name,
                Key=json_key,
                Body=json_data.encode('utf-8'),
                ContentType='application/json'
            )
            json_url = f"https://storage.yandexcloud.net/{self.bucket_name}/{json_key}"
            return {'success': True, 'url': json_url, 'key': json_key}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def get_metadata(self, object_name):
        """Получить метаданные из JSON файла рядом с фото"""
        try:
            json_key = object_name.rsplit('.', 1)[0] + '.json'
            response = self.client.get_object(Bucket=self.bucket_name, Key=json_key)
            json_data = response['Body'].read().decode('utf-8')
            metadata = json.loads(json_data)
            return {'success': True, 'metadata': metadata}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def delete_file(self, object_name):
        """Удалить файл и его метаданные"""
        try:
            # Удаляем фото
            self.client.delete_object(Bucket=self.bucket_name, Key=object_name)
            # Удаляем JSON с метаданными
            json_key = object_name.rsplit('.', 1)[0] + '.json'
            try:
                self.client.delete_object(Bucket=self.bucket_name, Key=json_key)
            except:
                pass
            return {'success': True}
        except Exception as e:
            return {'success': False, 'error': str(e)}
