FROM nginx:alpine
# Удаляем дефолтный конфиг Nginx
RUN rm /etc/nginx/conf.d/default.conf
# Копируем наш конфиг
COPY nginx.conf /etc/nginx/conf.d/default.conf
# Копируем файлы фронтенда
COPY . /usr/share/nginx/html