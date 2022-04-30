FROM python:3.10.4

WORKDIR /src

ARG CACHEBREAKER=1

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD [ "python", "./bot.py" ]