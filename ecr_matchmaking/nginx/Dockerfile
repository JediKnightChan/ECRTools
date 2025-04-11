FROM nginx:stable-alpine
RUN rm /etc/nginx/conf.d/default.conf
COPY nginx/server.conf /etc/nginx/conf.d

# Remove symlinks and create actual log files
RUN rm /var/log/nginx/access.log /var/log/nginx/error.log && \
    touch /var/log/nginx/access.log /var/log/nginx/error.log \
