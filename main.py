import json


def find_mac():
    with open('response.json') as f:
        response = json.load(f)

    textdetections = response['TextDetections']
    for textdetection in textdetections:
        if "MAC" in textdetection['DetectedText']:
            ans = textdetection['DetectedText']
            return ans + " was sent to IT. They'll connect you to the network!"
    return "No MAC Address in screenshot"


print(find_mac())

