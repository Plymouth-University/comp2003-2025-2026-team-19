FROM nginx:alpine

# Remove the default Nginx configuration file
RUN rm /etc/nginx/conf.d/default.conf

COPY nginx.conf /etc/nginx/conf.d/default.conf

HEALTHCHECK --interval=30s --timeout=3s \
    CMD curl -H "User-Agent: ferrytracker-healthcheck" -f http://localhost/health || exit 1