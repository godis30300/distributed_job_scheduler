FROM postgres:16

# Copy SQL scripts to initialize the database
COPY schema.sql /docker-entrypoint-initdb.d/01-schema.sql
COPY seed.sql /docker-entrypoint-initdb.d/02-seed.sql

# The official postgres image will automatically execute any .sql scripts in this directory
