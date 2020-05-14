FROM python:3.7-alpine

ENV PYTHONUNBUFFERED 1

RUN sed -i 's/dl-cdn.alpinelinux.org/mirrors.aliyun.com/g' /etc/apk/repositories
RUN apk update \
    && apk add --virtual build-deps gcc python3-dev musl-dev \
    && apk add make \
    ;

COPY ./requirements /requirements
RUN pip install -i https://mirrors.aliyun.com/pypi/simple/ --default-timeout=1000 -r /requirements/base.txt

COPY . /app
WORKDIR /app

EXPOSE 8200

CMD [ "make", "run" ]
