FROM python:3.9.1
RUN pip install tradedangerous
ENTRYPOINT [ "trade" ]