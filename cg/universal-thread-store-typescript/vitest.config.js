export default {
  test: {
    include: ['tests/test_*.*'],
    globals: true,
    coverage: {
      include: ['src/**'],
    },
  }
}
