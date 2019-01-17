FROM python:3.7
LABEL MAINTAINER=0xbug
ENV TZ=Asia/Shanghai
EXPOSE 80
ARG DEBIAN_FRONTEND=noninteractive
RUN mv /etc/apt/sources.list /etc/apt/sources.list.bak && \
    echo "deb http://mirrors.163.com/debian/ jessie main non-free contrib" >/etc/apt/sources.list && \
    echo "deb http://mirrors.163.com/debian/ jessie-proposed-updates main non-free contrib" >>/etc/apt/sources.list && \
    echo "deb-src http://mirrors.163.com/debian/ jessie main non-free contrib" >>/etc/apt/sources.list && \
    echo "deb-src http://mirrors.163.com/debian/ jessie-proposed-updates main non-free contrib" >>/etc/apt/sources.list
RUN apt-get update
RUN apt-get install --no-install-recommends -y curl gnupg git redis-server supervisor software-properties-common wget
RUN curl https://openresty.org/package/pubkey.gpg | apt-key add -
RUN add-apt-repository -y "deb http://openresty.org/package/debian $(lsb_release -sc) openresty"
RUN apt-get update
RUN apt-get install -y openresty
COPY ./deploy /Hawkeye/deploy
RUN pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -r /Hawkeye/deploy/pyenv/requirements.txt -U
RUN cp /Hawkeye/deploy/nginx/*.conf /usr/local/openresty/nginx/conf/
RUN cp /Hawkeye/deploy/supervisor/*.conf /etc/supervisor/conf.d/
COPY ./client/dist /Hawkeye/client/dist
COPY ./server /Hawkeye/server
WORKDIR /Hawkeye/server
CMD ["/usr/bin/supervisord", "-n", "-c", "/etc/supervisor/supervisord.conf"]