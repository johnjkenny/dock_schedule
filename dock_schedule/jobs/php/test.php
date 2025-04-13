<?php
echo "Hello, World!" . PHP_EOL;
$code = isset($argv[1]) ? intval($argv[1]) : 0;
echo "Exiting with code: $code" . PHP_EOL;
exit($code);
?>
