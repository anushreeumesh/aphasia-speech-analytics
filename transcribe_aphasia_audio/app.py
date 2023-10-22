import json
import boto3
import time
from datetime import datetime

client = boto3.client('transcribe')
s3c = boto3.client('s3')


def transcribe_aphasia_audio(bucket, key, patient_id):

    output_bucket = 'aphasia-audio-transcripts'

    job_name = patient_id + '-aphasia-patient-audio-transcription-' + \
        str(int(time.time()))

    response = client.start_transcription_job(
        TranscriptionJobName=job_name,
        IdentifyLanguage=True,
        Media={
            'MediaFileUri': f's3://{bucket}/{key}'
        },
        Settings={
            'ShowSpeakerLabels': True,
            'MaxSpeakerLabels': 2
        },
        OutputBucketName=output_bucket,
        OutputKey=patient_id + '-audio-transcript-' +
        str(int(time.time())) + ".json"
    )


def lambda_handler(event, context):

    print(event)

    bucket = event['Records'][0]['s3']['bucket']['name']
    key = event['Records'][0]['s3']['object']['key']

    patient_id = key.split("/")[-1].split("_")[0]

    transcribe_aphasia_audio(bucket, key, patient_id)

    return {
        'statusCode': 200,
        'body': json.dumps('Transcribed aphasia patient audio!')
    }
