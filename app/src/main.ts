import { mount } from "svelte";
import "./app.css";
import App from "./App.svelte";

// Default theme; App.svelte will overwrite once read_settings completes.
document.documentElement.dataset.theme = "light";

const app = mount(App, {
  target: document.getElementById("app")!,
});

export default app;
