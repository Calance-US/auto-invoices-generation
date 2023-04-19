import json
import boto3
from s3_utils import read_s3_file_into_dataframe
from process import process_dataframe_to_json
from process import generate_html_invoice
from process import get_download_url_after_s3_upload


def lambda_handler(event, context):
    """Sample pure Lambda function

    Parameters
    ----------
    event: dict, required
        API Gateway Lambda Proxy Input Format

        Event doc: https://docs.aws.amazon.com/apigateway/latest/
        developerguide/set-up-lambda-proxy-integrations.html#
        api-gateway-simple-proxy-for-lambda-input-format

    context: object, required
        Lambda Context runtime methods and attributes

        Context doc: https://docs.aws.amazon.com/lambda/latest/
        dg/python-context-object.html

    Returns
    ------
    API Gateway Lambda Proxy Output Format: dict

        Return doc: https://docs.aws.amazon.com/apigateway/latest/
        developerguide/set-up-lambda-proxy-integrations.html
    """

    bucket_name = event["Records"][0]["s3"]["bucket"]["name"]
    key = event["Records"][0]["s3"]["object"]["key"]

    print("Processing following key {} in bucket {}".format(
        key, bucket_name    
    ))

    df = read_s3_file_into_dataframe(bucket_name, key)
    json_output = process_dataframe_to_json(df, key)

    print("====== Got {} invoices to process =======".format(len(json_output)))

    htmls = list(map(lambda x: generate_html_invoice(x), json_output))
    download_url = get_download_url_after_s3_upload(
        bucket_name, key, htmls
    )

    print("The download link of the file is {}".format(download_url))

    return {
        "statusCode": 200,
        "body": json.dumps({
            "message": "successfully processed invoice {}".format(key),
        }),
    }
