static int emphasize(int value) {
    return value * value;
}

static int calculate(int value) {
    return emphasize(value) + 1;
}

int main(void) {
    return calculate(2);
}
