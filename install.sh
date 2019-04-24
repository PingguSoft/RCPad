## install.sh

sudo cp ./libraspidmx.so.1 /usr/lib

sudo rm -rf /opt/retropie/configs/all/RCPad-Pie/
sudo cp -f -r ./RCPad-Pie /opt/retropie/configs/all/

sudo chmod +x /opt/retropie/configs/all/RCPad-Pie/pngview

sudo sed -i '/RCPad-Pie.py/d' /opt/retropie/configs/all/autostart.sh
sudo sed -i '1i\\/usr/bin/python /opt/retropie/configs/all/RCPad-Pie/RCPad-Pie.py &' /opt/retropie/configs/all/autostart.sh

echo
echo "Setup Completed. Reboot after 3 Seconds."
#sleep 3
#sudo reboot
/usr/bin/python /opt/retropie/configs/all/RCPad-Pie/RCPad-Pie.py &
