import os
import os
import urllib
import boto3
import logging
from botocore.vendored import requests

SUPPORTED_TYPES = ['image/jpeg', 'image/jpg', 'image/png']  # Supported image types
MAX_SIZE = 5242880  # Max number of image bytes supported by Amazon Rekognition (5MiB)

VERIFICATION_TOKEN = os.environ['VERIFICATION_TOKEN']  # Slack verification token from environment variables
ACCESS_TOKEN = os.environ['ACCESS_TOKEN']  # Slack OAuth access token from environment variables

rekognition = boto3.client('rekognition')


def lambda_handler(event, context):
    if 'X-Slack-Retry-Num' in event['headers']:
        slk_retry = event['headers']['X-Slack-Retry-Num']
        return 200
    else:

        try:
            event = event['body']
            print('Validating message...')
            if not verify_token(event):  # Ignore event if verification token presented doesn't match
                return

            if event.get('challenge') is not None:  # Respond to Slack event subscription URL verification challenge
                print('Presented with URL verification challenge- responding accordingly...')
                challenge = event['challenge']
                return {'challenge': challenge}

            if not validate_event(event,
                                  event['token']):  # Ignore event if Slack message doesn't contain any supported images
                return

            event_details = event['event']
            file_details = event_details['files'][0]

            # file_id = event_details['file_id']
            # args = {
            # "token": token,
            # "file": file_id
            # }
            # response = requests.get('https://slack.com/api/files.info', params=args).json()

            # channel = response['file']['channels'][0]
            # url = response['file']['url_private']

            channel = event_details['channel']
            url = file_details['url_private']
            file_id = file_details['id']

            print('Downloading image...')
            image_bytes = download_image(url)
            print('Checking for MAC Address...')
            message = find_mac(image_bytes)
            post_message(channel, message)

        except Exception as error:
            logging.exception("message")


def verify_token(event):
    """ Verifies token presented in incoming event message matches the token copied when creating Slack app.

    Args:
        event (dict): Details about incoming event message, including verification token.

    Returns:
        (boolean)
        True if presented with the valid token.
        False otherwise.

    """
    if event['token'] != VERIFICATION_TOKEN:
        print('Presented with invalid token- ignoring message...')
        return False
    return True


def validate_event(event, token):
    """ Validates event by checking contained Slack message for image of supported type and size.

    Args:
        event (dict): Details about Slack message and any attachments.

    Returns:
        (boolean)
        True if event contains Slack message with supported image size and type.
        False otherwise.
    """
    event_details = event['event']
    print(event_details)  # added
    file_subtype = event_details.get('subtype')
    # file_type = event_details.get('type')

    # if file_type != 'file_shared':
    #     print('Not a file_shared event- ignoring event...')
    #     return False

    # file_id = event_details['file_id']
    # args = {
    #     "token": token,
    #     "file": file_id
    # }
    # response = requests.get('https://slack.com/api/files.info', params=args).json()
    # print(response)
    # mime_type = response['file']['mimetype']
    # file_size = response['file']['size']

    if file_subtype != 'file_share':
        print('Not a file_shared event- ignoring event...')
        return False

    file_details = event_details['files'][0]
    mime_type = file_details['mimetype']
    file_size = file_details['size']

    if mime_type not in SUPPORTED_TYPES:
        print('File is not an image- ignoring event...')
        return False

    if file_size > MAX_SIZE:
        print('Image is larger than 5MB and cannot be processed- ignoring event...')
        return False

    return True


def download_image(url):
    """ Download image from private Slack URL using bearer token authorization.

    Args:
        url (string): Private Slack URL for uploaded image.

    Returns:
        (bytes)
        Blob of bytes for downloaded image.


    """
    request = urllib.request.Request(url, headers={'Authorization': 'Bearer %s' % ACCESS_TOKEN})
    return urllib.request.urlopen(request).read()


def find_mac(image_bytes):
    """ Checks image for MAC Address text using Amazon Rekoginition's text detection deep learning feature.

    Args:
        image_bytes (bytes): Blob of image bytes.

    Returns:
        (string)
        Confirmation text sent if text detection finds MAC Address in blob of image bytes.
        Failed to find MAC Address text sent otherwise.

    """
    try:
        response = rekognition.detect_text(
            Image={
                'Bytes': image_bytes,
            }
        )
    except Exception as e:
        print(e)
        print('Unable to detect text in image.')
        raise (e)

    textdetections = response['TextDetections']
    for textdetection in textdetections:
        if "MAC Address" in textdetection['DetectedText']:
            ans = textdetection['DetectedText']
            return ans + " was sent to IT. They'll connect you to the network!"
    return "No MAC Address in screenshot"


def post_message(channel, message):
    """ Posts message to Slack channel via Slack API.

    Args:
        channel (string): Channel, private group, or IM channel to send message to. Can be an encoded ID, or a name.
        message (string): Message to post to channel

    Returns:
        (None)
    """
    url = 'https://slack.com/api/chat.postMessage'
    data = urllib.parse.urlencode(
        (
            ("token", ACCESS_TOKEN),
            ("channel", channel),
            ("text", message)
        )
    )
    data = data.encode("ascii")
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    request = urllib.request.Request(url, data, headers)
    urllib.request.urlopen(request)