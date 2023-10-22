import json
import boto3
from datetime import datetime
import time
import tempfile
import os

s3c = boto3.client('s3')
bdrkc = boto3.client(service_name="bedrock", region_name='us-west-2')
bdrkrtc = boto3.client(service_name="bedrock-runtime", region_name='us-west-2')


def analyse_transcription_result(transcript_json, patient_id):

    # Extract transcript text to send to Amazon Bedrock / Claude / Virtual Speech Pathologist

    for transcript in transcript_json['results']['transcripts']:
        patient_transcript_text = transcript['transcript']

    virtual_speech_pathologist_llm_prompt = "\n\nHuman: You are a speech pathologist reviewing the language of a patient who has aphasia. Respond with the areas of the speech that show the patient has semantic paraphasia. Also provide a summary of the condition of patient. the following text is a person with aphasia communicating with a variety of people -" + patient_transcript_text + "\n\nAssistant: "

    body = json.dumps(
        {
            "prompt": virtual_speech_pathologist_llm_prompt,
            "max_tokens_to_sample": 10000,
        }
    )

    bdrk_response = bdrkrtc.invoke_model(
        body=body, modelId="anthropic.claude-v2")

    bdrk_response_body = json.loads(bdrk_response.get("body").read())

    vsp_json_file_name = patient_id + '-virtual-speech-pathologist-report-' + \
        str(int(time.time())) + '.json'

    # Upload response from Bedrock / Claude / Virtual Speech Pathologist to Amazon S3

    temp_dir = tempfile.mkdtemp()
    vsp_json_file_path = os.path.join(temp_dir, vsp_json_file_name)

    with open(vsp_json_file_path, 'w') as f:
        json.dump(bdrk_response_body, f)

    s3c.upload_file(vsp_json_file_path, 'aphasia-speech-analytics-reports',
                    'virtual-speech-pathologist-reports/' + patient_id + '/' + vsp_json_file_name)

    # Create a "Words Spoken Report"

    spk_0_total_time, spk_1_total_time, total_legible_time_spoken = 0, 0, 0

    for item in transcript_json['results']['items']:

        if item['type'] == 'pronunciation':
            start_time = float(item['start_time'])
            end_time = float(item['end_time'])
            current_speaker = item['speaker_label']

            if current_speaker == 'spk_0':
                spk_0_total_time += end_time - start_time

            if current_speaker == 'spk_1':
                spk_1_total_time += end_time - start_time

    total_time_spoken = max(spk_0_total_time, spk_1_total_time)

    primary_speaker = 'spk_0' if spk_0_total_time > spk_1_total_time else 'spk_1'

    words_spoken, legible_words, illegible_words, unique_words_spoken = [], [], [], []

    for item in transcript_json['results']['items']:

        if item['type'] == 'pronunciation':
            current_speaker = item['speaker_label']

            if current_speaker == primary_speaker:
                words_spoken.append(item['alternatives'][0]['content'].lower())

                if float(item['alternatives'][0]['confidence']) > 0.95:
                    legible_words.append(
                        item['alternatives'][0]['content'].lower())
                    total_legible_time_spoken += float(
                        item['end_time']) - float(item['start_time'])

                else:
                    illegible_words.append(
                        item['alternatives'][0]['content'].lower())

    word_report_json = {}
    for word in words_spoken:
        if word not in unique_words_spoken:
            unique_words_spoken.append(word)

        word_report_json["patient_id"] = patient_id
        word_report_json["date"] = datetime.now().strftime("%d/%m/%Y")
        word_report_json["time"] = datetime.now().strftime("%H:%M:%S")
        word_report_json["word_spoken"] = word

        word_json_data = json.dumps(word_report_json)

        word_report_name = patient_id + '-aphasia-patient-word-report-' + \
            str(int(time.time())) + '-' + word + '.json'
        temp_dir = tempfile.mkdtemp()
        word_report_file_path = os.path.join(temp_dir, word_report_name)

        with open(word_report_file_path, 'w') as f:
            f.write(word_json_data)

        s3c.upload_file(word_report_file_path, 'aphasia-speech-analytics-reports',
                        'word-reports/' + patient_id + '/' + word_report_name)

    # Create an "Aphasia Patient Summary" Report

    summary_report_json = {
        "patient_id": patient_id,
        "date": datetime.now().strftime("%d/%m/%Y"),
        "time": datetime.now().strftime("%H:%M:%S"),
        "total_time_spoken": total_time_spoken,
        "total_legible_time_spoken": total_legible_time_spoken,
        "total_recording_duration": spk_0_total_time + spk_1_total_time,
        "word_count": len(words_spoken),
        "legible_word_count": len(legible_words),
        "illegible_word_count": len(illegible_words),
        "unique_word_count": len(unique_words_spoken),
        "legibility_score": (len(legible_words)/len(words_spoken))*100,
    }

    summary_report_name = patient_id + \
        '-aphasia-patient-summary-report-' + str(int(time.time())) + '.json'

    temp_dir = tempfile.mkdtemp()
    summary_report_file_path = os.path.join(temp_dir, summary_report_name)

    with open(summary_report_file_path, 'w') as f:
        json.dump(summary_report_json, f)

    s3c.upload_file(summary_report_file_path, 'aphasia-speech-analytics-reports',
                    'summary-reports/' + patient_id + '/' + summary_report_name)


def lambda_handler(event, context):

    print(event)

    s3_bucket = event['Records'][0]['s3']['bucket']['name']
    s3_key = event['Records'][0]['s3']['object']['key']

    patient_id = s3_key.split("-")[0]

    # Download the JSON file from S3
    response = s3c.get_object(Bucket=s3_bucket, Key=s3_key)
    json_content = response['Body'].read().decode('utf-8')

    # Parse the JSON content into a Python dictionary
    transcript_json = json.loads(json_content)

    analyse_transcription_result(transcript_json, patient_id)

    return {
        'statusCode': 200,
        'body': json.dumps('Analysed aphasia patient transcript!')
    }
