F='%{time_connect} %{time_appconnect} %{time_starttransfer} %{time_total} %{http_code}\n'
probe(){ name=$1; url=$2; : > "$name.txt"; for i in $(seq 1 10); do curl -s -o /dev/null -w "$F" "$url" >> "$name.txt"; done;
  # warm: reuse connection, 10 requests in one curl
  args=""; for i in $(seq 1 10); do args="$args $url"; done
  curl -s -o /dev/null -o /dev/null -o /dev/null -o /dev/null -o /dev/null -o /dev/null -o /dev/null -o /dev/null -o /dev/null -o /dev/null -w "$F" $args > "$name.warm.txt"; }
probe fe https://archi-tinder.vercel.app/
probe api_meta https://archi-tinder.up.railway.app/api/v1/auth/meta/roles/
probe aws_seoul https://dynamodb.ap-northeast-2.amazonaws.com/
probe aws_tokyo https://dynamodb.ap-northeast-1.amazonaws.com/
probe aws_sg https://dynamodb.ap-southeast-1.amazonaws.com/
curl -sI https://archi-tinder.up.railway.app/api/v1/auth/meta/roles/ | grep -iE "^(HTTP|x-railway|server|content-type)"
