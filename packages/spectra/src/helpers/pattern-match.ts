export const isPatternMatch = (input: string, pattern: RegExp) => {
  pattern.lastIndex = 0;
  return pattern.test(input);
};
