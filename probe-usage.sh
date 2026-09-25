K=$(sudo -u postgres psql -d pvnetwork_panel -t -A -c "select key from nodes where address='77.110.126.47'")
curl -s --connect-timeout 5 -X GET -H "Content-Type: application/json" -d '{}' -H "X-PVNetwork-Node-Key: $K" -H "X-OV-Node-Key: $K" "http://77.110.126.47:9090/sync/usage" | head -c 600; echo
