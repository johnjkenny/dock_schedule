#!/bin/bash

echo "Hello, World!"
code="${1:-0}"
echo "Exiting with code: $code"
exit "$code"
