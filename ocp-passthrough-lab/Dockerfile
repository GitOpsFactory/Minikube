
FROM nginxinc/nginx-unprivileged:stable-alpine

COPY app/index.html /usr/share/nginx/html/index.html

COPY nginx/default.conf /etc/nginx/conf.d/default.conf

EXPOSE 8443
