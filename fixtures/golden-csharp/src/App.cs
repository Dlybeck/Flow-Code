namespace Demo;

static class App
{
    static int Emphasize(int value)
    {
        return value * value;
    }

    static int Calculate(int value)
    {
        return Emphasize(value) + 1;
    }

    static int Main(string[] args)
    {
        return Calculate(2);
    }
}
