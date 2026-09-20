package demo;

final class App {
    static int emphasize(int value) {
        return value * value;
    }

    static int calculate(int value) {
        return emphasize(value) + 1;
    }

    public static int main(String[] args) {
        return calculate(2);
    }
}
