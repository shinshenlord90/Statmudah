#!/bin/sh
# Bina pakej .deb StatMudah. Guna: sh build_deb.sh
set -e
cd "$(dirname "$0")"
V=$(sed -n 's/^VERSION = "\(.*\)"/\1/p' statmudah.py)
P=build/statmudah_${V}_all
rm -rf build && mkdir -p $P/DEBIAN $P/usr/bin $P/usr/share/applications $P/usr/share/statmudah
install -m755 statmudah.py $P/usr/share/statmudah/
install -m644 smstats.py i18n.py $P/usr/share/statmudah/
ln -s ../share/statmudah/statmudah.py $P/usr/bin/statmudah
cat > $P/DEBIAN/control <<EOF
Package: statmudah
Version: $V
Section: math
Priority: optional
Architecture: all
Depends: python3 (>= 3.10), python3-tk
Maintainer: StatMudah <statmudah@localhost>
Description: Aplikasi statistik mudah (seperti PSPP) bergaya Windows 7
 Penyediaan data (kes berulang, julat sah, data hilang, item songsang,
 skor konstruk), deskriptif dan normaliti, korelasi, ujian-t, ANOVA,
 ujian bukan parametrik, khi kuasa dua, regresi linear dan logistik,
 saiz kesan, ayat laporan APA dan eksport HTML untuk Word. BM/English.
EOF
cat > $P/usr/share/applications/statmudah.desktop <<EOF
[Desktop Entry]
Name=StatMudah
Comment=Analisis statistik mudah
Exec=statmudah
Icon=accessories-calculator
Terminal=false
Type=Application
Categories=Education;Science;Math;
EOF
dpkg-deb --root-owner-group --build $P . >/dev/null
rm -rf build
echo "statmudah_${V}_all.deb"
