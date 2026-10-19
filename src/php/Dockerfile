FROM composer:2 AS framework
RUN composer create-project codeigniter/framework /ci 3.1.13 --no-interaction --no-dev --prefer-dist

FROM php:7.4-apache
RUN a2enmod rewrite && sed -i 's/AllowOverride None/AllowOverride All/' /etc/apache2/apache2.conf
COPY --from=framework /ci /var/www/html
COPY application /var/www/html/application
COPY .htaccess /var/www/html/.htaccess
RUN mkdir -p /var/www/html/application/cache /var/www/html/application/logs \
    && chown -R www-data:www-data /var/www/html/application/cache /var/www/html/application/logs
