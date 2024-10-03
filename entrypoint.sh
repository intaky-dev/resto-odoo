#!/bin/bash
set -e

# Asegura los permisos del directorio
mkdir -p /etc/odoo
chmod 777 /etc/odoo

# Leer la contraseña desde el archivo de secretos
DB_PASSWORD=$(cat /run/secrets/postgresql_password)

# Crea o actualiza odoo.conf
cat > /etc/odoo/odoo.conf <<EOF
[options]
admin_passwd = ${ADMIN_PASSWD:-admin}
db_host = ${HOST:-db}
db_port = ${PORT:-5432}
db_user = ${USER:-odoo}
db_password = ${DB_PASSWORD}
addons_path = /mnt/extra-addons,/usr/lib/python3/dist-packages/odoo/addons
EOF

echo "Odoo está listo para ser iniciado."
exec "$@"
