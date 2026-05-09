export default {
  test: {
    include: ['tests/test_*.*'],
    environment: 'happy-dom',
    globals: true,
    coverage: {
      include: ['src/**'],
    },
  }
}
