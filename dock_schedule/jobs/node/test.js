console.log("Hello, World!");
const args = process.argv.slice(2);
const code = parseInt(args[0], 10) || 0;
console.log(`Exiting with code: ${code}`);
process.exit(code);
