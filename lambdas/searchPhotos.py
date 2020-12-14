import json
import boto3
import os
import sys
import uuid
import time
from botocore.vendored import requests

ES_HOST = 'https://vpc-photos-tehaikmmz7dmfwpc2i2tgowvn4.us-east-1.es.amazonaws.com'
REGION = 'us-east-1'

def get_url(es_index, es_type, keyword):
    url = ES_HOST + '/' + es_index + '/' + es_type + '/_search?q=' + keyword.lower()
    return url

def lambda_handler(event, context):
	# recieve from API Gateway
	print("EVENT --- {}".format(json.dumps(event)))
	
	headers = { "Content-Type": "application/json" }
	lex = boto3.client('lex-runtime')

	query = event["queryStringParameters"]["q"]
	
	
	if query == "voiceSearch":
		transcribe = boto3.client('transcribe')
		job_name = time.strftime("%a %b %d %H:%M:%S %Y", time.localtime()).replace(":", "-").replace(" ", "")
		job_uri = "https://s3.amazonaws.com/photoss34/test.mp3" #frontend bucket
		transcribe.start_transcription_job(
		    TranscriptionJobName=job_name,
		    Media={'MediaFileUri': job_uri},
		    MediaFormat='mp3',
		    LanguageCode='en-US'
		)
		while True:
		    status = transcribe.get_transcription_job(TranscriptionJobName=job_name)
		    #print(status['TranscriptionJob']['TranscriptionJobStatus'])
		    if status['TranscriptionJob']['TranscriptionJobStatus'] in ['COMPLETED', 'FAILED']:
		        break
		    print("Not ready yet...")
		    time.sleep(3)
		print("Transcript URL: ", status)
		transcriptURL = status['TranscriptionJob']['Transcript']['TranscriptFileUri']
		trans_text = requests.get(transcriptURL).json()
		
		print("Transcripts: ", trans_text)
		print(trans_text["results"]['transcripts'][0]['transcript'])
		
		s3client = boto3.client('s3')
		response = s3client.delete_object(
		    Bucket='photoss34',
		    Key='test.mp3'
		)
		query = trans_text["results"]['transcripts'][0]['transcript']
		s3client.put_object(Body=query, Bucket='photoss34', Key='test.txt')
		return {
			'statusCode': 200,
			'headers': {
				"Access-Control-Allow-Origin": "*"
			},
			'body': "transcribe done"
		}
	
	if query == "voiceResult":
		s3client = boto3.client('s3')
		data = s3client.get_object(Bucket='photoss34', Key='test.txt')
		query = data.get('Body').read().decode('utf-8')
		print("Voice query: ", query)
		s3client.delete_object(
			Bucket='photoss34',
			Key='test.txt'
		)
	
	print("query---{}".format(query))
	print(lex, 'Lex')
	lex_response = lex.post_text(botName='voicealbumbot',botAlias='test',userId='sai',inputText=query)
	print(lex_response)
	print("LEX RESPONSE --- {}".format(json.dumps(lex_response)))

	slots = lex_response['slots']

	img_list = []
	for i, tag in slots.items():
		if tag:
			url = get_url('photos', '_doc', tag)
			print("ES URL --- {}".format(url))

			es_response = requests.get(url, headers=headers).json()
			print("ES RESPONSE --- {}".format(json.dumps(es_response)))

			es_src = es_response['hits']['hits']
			print("ES HITS --- {}".format(json.dumps(es_src)))

			for photo in es_src:
				labels = [word.lower() for word in photo['_source']['labels']]
				if tag in labels:
					objectKey = photo['_source']['objectKey']
					img_url = 'https://s3.amazonaws.com/photoss34/' + objectKey
					img_list.append(img_url)

	print(img_list)
	if img_list:
		print("img returned...")
		return {
			'statusCode': 200,
			'headers': {
				"Access-Control-Allow-Origin": "*",
				'Content-Type': 'application/json'
			},
			'body': json.dumps(img_list)
		}
	else:
		print("no img returend...")
		return {
			'statusCode': 200,
			'headers': {
				"Access-Control-Allow-Origin": "*",
				'Content-Type': 'application/json'
			},
			'body': json.dumps("No such photos.")
		}
		