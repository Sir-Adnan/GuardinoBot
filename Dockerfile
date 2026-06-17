FROM python:3.11.10-alpine

COPY ./requirements.txt /app/

WORKDIR /app

RUN pip install -r requirements.txt

COPY . /app

RUN chmod +x bot.py
RUN chmod +x prestart.sh

ENV PYTHONUNBUFFERED=1

CMD ./prestart.sh && ./bot.py