import pandas as pd
import boto3
import io
import os
import sys


s3 = boto3.client("s3")
session = boto3.Session()


def read_s3_file_into_dataframe(
        s3_bucket_name,
        filename,
):

    print("Converting to dataframe for {}".format(filename))

    response = s3.get_object(
        Bucket=s3_bucket_name,
        Key=filename,
        ResponseContentDisposition="attachment; filename={}".format(filename),
        ResponseContentType="application/vnd.ms-excel"
    )

    status = response.get("ResponseMetadata", {}).get("HTTPStatusCode")

    if status == 200:
        print(f"Successful S3 get_object response. Status - {status}")

        df = pd.read_excel(io.BytesIO(response.get('Body').read()))

        return df

    else:
        print(f"Unsuccessful S3 get_object response. Status - {status}")


def upload_s3_file_and_generate_url(s3_bucket_name, key, filepath):
    """
    uploads a file in s3 in specific path
    """

    s3_res = session.resource('s3')
    object = s3_res.Object(s3_bucket_name, key)
    result = object.put(Body=open(filepath, 'rb'))
    res = result.get('ResponseMetadata')

    if res.get('HTTPStatusCode') == 200:
        print('File Uploaded Successfully')
    else:
        print('File Not Uploaded')
        sys.exit()

    return s3.generate_presigned_url(
        'get_object',
        Params={
            "Bucket": s3_bucket_name,
            "Key": key
        },
    )
