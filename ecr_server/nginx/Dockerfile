FROM nginx:stable-alpine

# Install Fail2Ban, iptables, and supervisor
RUN apk update && apk add --no-cache \
    fail2ban \
    iptables \
    supervisor

# Copy your jail.local to configure Fail2Ban
COPY nginx/fail2ban/jail.conf /etc/fail2ban/jail.conf
COPY nginx/fail2ban/filter.d/ /etc/fail2ban/filter.d/
RUN rm /etc/fail2ban/jail.d/

RUN rm /etc/nginx/conf.d/default.conf
COPY nginx/server.conf /etc/nginx/conf.d

COPY nginx/supervisord.conf /etc/supervisord.conf

CMD ["/usr/bin/supervisord", "-c", "/etc/supervisord.conf"]
