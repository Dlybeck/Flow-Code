function emphasize(text) {
  return text.toUpperCase();
}

function formatGreeting(name) {
  return emphasize(`Hello, ${name}`);
}

function main() {
  console.log(formatGreeting("Flow-Code"));
}

main();
