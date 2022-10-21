FROM python:3.6

ADD code /code
RUN pip install -r /code/dependencies

WORKDIR /code
ENV PYTHONPATH '/code/'

CMD ["python" , "/code/exporter.py"]
