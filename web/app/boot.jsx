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
    willPlayIntro = !seen && !reduced && !window.EmpireData.skipIntro;
  } catch (_) {}
  if (willPlayIntro) document.documentElement.classList.add("ares-booting");
  const revealHub = () => document.documentElement.classList.remove("ares-booting");

  function Root() {
    const [isPhone, setIsPhone] = React.useState(() => matchMedia("(max-width: 620px)").matches);
    React.useEffect(() => {
      const media = matchMedia("(max-width: 620px)");
      const changed = (event) => setIsPhone(event.matches);
      media.addEventListener("change", changed);
      return () => media.removeEventListener("change", changed);
    }, []);
    // While the intro plays, the hub isn't built yet: building it (and loading its images)
    // at the same time made the slam stutter. It is built once the big motion is over.
    const [hubOn, setHubOn] = React.useState(!willPlayIntro || !window.EmpireIntro);
    React.useEffect(() => {
      if (!willPlayIntro) { revealHub(); return; }
      try { sessionStorage.setItem("empire-intro-seen", "1"); } catch (_) {}
      if (window.EmpireIntro) {
        // onReveal fires as the crossfade begins → the overlay dissolves straight into the hub
        window.EmpireIntro.play({
          reducedOk: true,
          // build + show the hub under the opaque intro, so it is fully drawn before the fade
          onSettled: () => { setHubOn(true); requestAnimationFrame(revealHub); },
          onReveal: () => { setHubOn(true); revealHub(); },
          onDone: revealHub,
        });
      } else {
        revealHub();
      }
    }, []);
    const App = isPhone ? window.EmpireMobile : window.EmpireApp;
    return hubOn && App ? <App /> : null;
  }

  ReactDOM.createRoot(document.getElementById("root")).render(<Root />);
})();
