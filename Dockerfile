FROM python:3.9.1
COPY . /
ENV DISPLAY
RUN pip install appJar \
  && pip install -r requirements/dev.txt
RUN python trade.py import -P eddblink -O clean,skipvend
ENTRYPOINT [ "python", "trade.py", "gui"]