/* Ares Empire — boot. Plays the molten-gold intro once per session (sessionStorage;
   honors prefers-reduced-motion), keeping the hub hidden behind the slam so the throne
   room never flashes before the intro morphs in. Then mounts the hub. */
(function () {
  // Decide SYNCHRONOUSLY (before first paint) whether the intro will play, so we can hide
  // the hub behind the bust-slam and never flash the empire first.
  let willPlayIntro = false;
  try {
    const seen = sessionStorage.getItem("empire-intro-seen");
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    willPlayIntro = !seen && !reduced;
  } catch (_) {}
  if (willPlayIntro) document.documentElement.classList.add("ares-booting");
  const revealHub = () => document.documentElement.classList.remove("ares-booting");

  function Root() {
    React.useEffect(() => {
      if (!willPlayIntro) { revealHub(); return; }
      try { sessionStorage.setItem("empire-intro-seen", "1"); } catch (_) {}
      if (window.EmpireIntro) {
        // onReveal fires as the crossfade begins → the overlay dissolves straight into the hub
        window.EmpireIntro.play({ reducedOk: true, onReveal: revealHub, onDone: revealHub });
      } else {
        revealHub();
      }
    }, []);
    const App = window.EmpireApp;
    return App ? <App /> : null;
  }

  ReactDOM.createRoot(document.getElementById("root")).render(<Root />);
})();
