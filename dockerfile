FROM odoo:15.0

USER root

# Instalación de dependencias
RUN apt-get update && apt-get install -y git \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Prepara el directorio y archivo de configuración con permisos adecuados
RUN mkdir -p /etc/odoo && \
    echo "[options]\nadmin_passwd = admin\ndb_host = db\ndb_port = 5432\ndb_user = odoo\ndb_password = postgres\naddons_path = /mnt/extra-addons,/usr/lib/python3/dist-packages/odoo/addons" > /etc/odoo/odoo.conf && \
    chown -R odoo: /etc/odoo && \
    chmod -R 755 /etc/odoo

COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]

USER odoo

CMD ["odoo"]
