FROM python:3.7
LABEL MAINTAINER=0xbug
ENV TZ=Asia/Shanghai
EXPOSE 80
RUN yum install -y curl gnupg git redis supervisor wget geoip openresty
COPY ./deploy /Hawkeye/deploy
RUN pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -r /Hawkeye/deploy/pyenv/requirements.txt -U
RUN cp /Hawkeye/deploy/nginx/*.conf /usr/local/openresty/nginx/conf/
RUN cp /Hawkeye/deploy/supervisor/*.conf /etc/supervisor/conf.d/
COPY ./client/dist /Hawkeye/client/dist
COPY ./server /Hawkeye/server
WORKDIR /Hawkeye/server
CMD ["/usr/bin/supervisord", "-n", "-c", "/etc/supervisor/supervisord.conf"]