import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  mount: vi.fn(),
  appComponent: { __mockApp: true } as unknown,
  appInstance: { __mockAppInstance: true } as unknown,
}));

vi.mock("svelte", () => ({
  mount: mocks.mount,
}));

vi.mock("../App.svelte", () => ({
  default: mocks.appComponent,
}));

vi.mock("../app.css", () => ({}));

describe("main entry", () => {
  beforeEach(() => {
    vi.resetModules();
    mocks.mount.mockReset();
    mocks.mount.mockReturnValue(mocks.appInstance);
    delete document.documentElement.dataset.theme;
    document.body.innerHTML = "";
    const root = document.createElement("div");
    root.id = "app";
    document.body.appendChild(root);
  });

  it("sets dataset.theme to light before mounting", async () => {
    let themeAtMount: string | undefined;
    mocks.mount.mockImplementation(() => {
      themeAtMount = document.documentElement.dataset.theme;
      return mocks.appInstance;
    });

    await import("../main");

    expect(themeAtMount).toBe("light");
    expect(document.documentElement.dataset.theme).toBe("light");
  });

  it("mounts the App component into #app", async () => {
    const target = document.getElementById("app");

    await import("../main");

    expect(mocks.mount).toHaveBeenCalledTimes(1);
    const [component, options] = mocks.mount.mock.calls[0];
    expect(component).toBe(mocks.appComponent);
    expect(options).toEqual({ target });
    expect(options.target).toBe(target);
  });

  it("default-exports the value returned by mount", async () => {
    const mainModule = await import("../main");

    expect(mainModule.default).toBe(mocks.appInstance);
  });
});
