#!/usr/bin/env bash

OUTPUT_DIRECTORY=/var/lib/marzban/static/

install_geodata() {
    download_geodata() {
        if ! curl -R -H 'Cache-Control: no-cache' -o "${dir_tmp}/${2}" "${1}"; then
            echo 'error: Download failed! Please check your network or try again.'
            exit 1
        fi
    }
    local URL_GEOSITE_IR="https://raw.githubusercontent.com/Chocolate4U/Iran-sing-box-rules/rule-set/geosite-ir.srs"
    local URL_GEOSITE_CATEGORY_ADS_ALL="https://raw.githubusercontent.com/Chocolate4U/Iran-sing-box-rules/rule-set/geosite-category-ads-all.srs"
    local URL_GEOSITE_MALWARE="https://raw.githubusercontent.com/Chocolate4U/Iran-sing-box-rules/rule-set/geosite-malware.srs"
    local URL_GEOSITE_PHISHING="https://raw.githubusercontent.com/Chocolate4U/Iran-sing-box-rules/rule-set/geosite-phishing.srs"
    local URL_GEOSITE_CRYPTO_MINERS="https://raw.githubusercontent.com/Chocolate4U/Iran-sing-box-rules/rule-set/geosite-cryptominers.srs"
    local URL_GEOIP_IR="https://raw.githubusercontent.com/Chocolate4U/Iran-sing-box-rules/rule-set/geoip-ir.srs"
    local URL_GEOIP_MALWARE="https://raw.githubusercontent.com/Chocolate4U/Iran-sing-box-rules/rule-set/geoip-malware.srs"
    local URL_GEOIP_PHISHING="https://raw.githubusercontent.com/Chocolate4U/Iran-sing-box-rules/rule-set/geoip-phishing.srs"

    local FILE_GEOSITE_IR="geosite-ir.srs"
    local FILE_GEOSITE_CATEGORY_ADS_ALL="geosite-category-ads-all.srs"
    local FILE_GEOSITE_MALWARE="geosite-malware.srs"
    local FILE_GEOSITE_PHISHING="geosite-phishing.srs"
    local FILE_GEOSITE_CRYPTO_MINERS="geosite-cryptominers.srs"
    local FILE_GEOIP_IR="geoip-ir.srs"
    local FILE_GEOIP_MALWARE="geoip-malware.srs"
    local FILE_GEOIP_PHISHING="geoip-phishing.srs"

    local dir_tmp
    dir_tmp="$(mktemp -d)"

    download_geodata $URL_GEOSITE_IR $FILE_GEOSITE_IR
    download_geodata $URL_GEOSITE_CATEGORY_ADS_ALL $FILE_GEOSITE_CATEGORY_ADS_ALL
    download_geodata $URL_GEOSITE_MALWARE $FILE_GEOSITE_MALWARE
    download_geodata $URL_GEOSITE_PHISHING $FILE_GEOSITE_PHISHING
    download_geodata $URL_GEOSITE_CRYPTO_MINERS $FILE_GEOSITE_CRYPTO_MINERS
    download_geodata $URL_GEOIP_IR $FILE_GEOIP_IR
    download_geodata $URL_GEOIP_MALWARE $FILE_GEOIP_MALWARE
    download_geodata $URL_GEOIP_PHISHING $FILE_GEOIP_PHISHING

    mkdir -p "$OUTPUT_DIRECTORY"
    cp "${dir_tmp}"/${FILE_GEOSITE_IR} "${OUTPUT_DIRECTORY}"/${FILE_GEOSITE_IR}
    cp "${dir_tmp}"/${FILE_GEOSITE_CATEGORY_ADS_ALL} "${OUTPUT_DIRECTORY}"/${FILE_GEOSITE_CATEGORY_ADS_ALL}
    cp "${dir_tmp}"/${FILE_GEOSITE_MALWARE} "${OUTPUT_DIRECTORY}"/${FILE_GEOSITE_MALWARE}
    cp "${dir_tmp}"/${FILE_GEOSITE_PHISHING} "${OUTPUT_DIRECTORY}"/${FILE_GEOSITE_PHISHING}
    cp "${dir_tmp}"/${FILE_GEOSITE_CRYPTO_MINERS} "${OUTPUT_DIRECTORY}"/${FILE_GEOSITE_CRYPTO_MINERS}
    cp "${dir_tmp}"/${FILE_GEOIP_IR} "${OUTPUT_DIRECTORY}"/${FILE_GEOIP_IR}
    cp "${dir_tmp}"/${FILE_GEOIP_MALWARE} "${OUTPUT_DIRECTORY}"/${FILE_GEOIP_MALWARE}
    cp "${dir_tmp}"/${FILE_GEOIP_PHISHING} "${OUTPUT_DIRECTORY}"/${FILE_GEOIP_PHISHING}

    rm -r "${dir_tmp}"
    exit 0
}

install_geodata
