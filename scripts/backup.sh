#!/bin/bash

TOKEN=""
CHATID=""

MYSQL_ROOT_PASSWORD=""

PREFIX="marzbot"
CAPTION="marzbot backup files"

VAR_DIR="/var/lib/marzbot"
OPT_DIR="/opt/marzbot"
BACKUP_DIR="backups"
DELETE_PREV=true


if [ "$DELETE_PREV" = true ]; then
	echo "deleting old backups"
    rm -r $BACKUP_DIR
fi


date="$(date +%F_%H-%M-%S)"

OUTPUT_DIR="$BACKUP_DIR/$PREFIX-$date"

if [ -n "$BACKUP_DIR" ]; then
	if [ ! -d "$BACKUP_DIR" ]; then
		echo "Creating backup direcotry at: $BACKUP_DIR"
		mkdir $BACKUP_DIR
	fi
fi

echo "Changing working directory to $BACKUP_DIR"
mkdir -p $OUTPUT_DIR

# dump marzbot-db
docker exec marzbot-db-1 mariadb-dump -u root --password=$MYSQL_ROOT_PASSWORD --all-databases > "$OUTPUT_DIR/marzbot.sql"

# copy redis dump file
redis="marzbot-redis-1"
docker exec $redis redis-cli save
docker cp $redis:/data/dump.rdb "$OUTPUT_DIR/dump.rdb"

cp -R "$OPT_DIR" "$OUTPUT_DIR/marzbot-opt/"
cp -R "$VAR_DIR" "$OUTPUT_DIR/marzbot-var/"
rm -r "$OUTPUT_DIR/marzbot-var/docker-volumes/" # no need to copy it

echo "creating archive file in '$OUTPUT_DIR'"
TAR_FILE="$OUTPUT_DIR.tar.gz"

tar -zcf $TAR_FILE $OUTPUT_DIR

echo "Uploading file to telegram..."
curl -F chat_id="$CHATID" -F caption="$CAPTION" -F parse_mode="HTML" -F document=@"$TAR_FILE" https://api.telegram.org/bot${TOKEN}/sendDocument
echo "Backup finished!"