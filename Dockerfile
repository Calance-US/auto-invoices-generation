FROM public.ecr.aws/lambda/python:3.8

COPY requirements.txt ./

RUN pip install -r requirements.txt

COPY app.py ./src/process.py ./src/s3_utils.py ./template/index.html ./

CMD ["app.lambda_handler"]
