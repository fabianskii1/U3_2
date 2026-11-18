// Group independent Zustand stores under one DevTools connection.
export const devtoolsOptions = (store: string) => ({
  name: "SKADI",
  store,
  enabled: import.meta.env.DEV,
});
