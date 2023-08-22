#!/bin/sh

cmd() {
  python3 ./main.py &
}

cmd
PID="$!"

close() {
  echo "Shutting down..."
  kill "$PID"
}

trap close INT QUIT TERM EXIT

echo "Started watching"
while inotifywait -e modify ./friends_queue/*.py ./friends_queue/*.css ./main.py; do
  echo "Restarting"
  kill "$PID"
  cmd
  PID="$!"
done

kill "$PID"
