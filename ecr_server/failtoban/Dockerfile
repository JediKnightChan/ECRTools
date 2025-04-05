# Use a base image that has fail2ban installed (such as an Alpine image)
FROM alpine:latest

# Install Fail2Ban and other required dependencies
RUN apk update && apk add --no-cache \
    fail2ban \
    iptables \
    bash

# Copy your jail.conf to configure Fail2Ban
COPY failtoban/jail.conf /etc/fail2ban/jail.conf
COPY failtoban/filter.d/ /etc/fail2ban/filter.d/
RUN rm -rf /etc/fail2ban/jail.d/

# Command to start Fail2Ban
CMD /usr/bin/fail2ban-server start && tail -f /dev/null