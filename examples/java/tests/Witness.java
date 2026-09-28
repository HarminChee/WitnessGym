public final class Witness {
    public static void main(String[] args) {
        if (Logic.clamp(2) != 2) {
            throw new AssertionError("WITNESS_TARGET: positive value must be preserved");
        }
    }
}
