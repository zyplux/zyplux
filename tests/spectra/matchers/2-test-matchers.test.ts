import { describe, expect, test } from './matchers.ts';

describe('2.1 checking collections', () => {
  test('2.1.1 collection matchers compare nested elements, duplicates, and element counts', () => {
    expect([{ id: 1 }, { id: 2 }]).toContainExactElementsInAnyOrder([{ id: 2 }, { id: 1 }]);
    expect([{ id: 1 }, { id: 2 }]).toContainNoDuplicates();
    expect(() => {
      expect([1, 1]).toContainNoDuplicates();
    }).toThrow('duplicates:\n  1');
    expect(() => {
      expect(['alpha', 'alpha']).toContainExactElementsInAnyOrder(['alpha', 'beta']);
    }).toThrow('missing:\n  beta\nextra:\n  alpha');
    const elements = ['alpha', 'beta'];
    expect(elements).toHaveNumberOfElements(elements.length);
    expect(() => {
      expect(elements).toHaveNumberOfElements(elements.length + 1);
    }).toThrow('(2 elements) to have 3 elements');
  });
});
