"use strict";

let seekBar = null;
let timeBefore = null;
let timeAfter = null;

function getTimeElms() {
  if (seekBar === null) {
    seekBar = document.querySelector(".seek-bar");
    timeBefore = seekBar.querySelector("span:first-child");
    timeAfter = seekBar.querySelector("span:last-child");
  }
  return [timeBefore, timeAfter];
}

function durationToStr(duration) {
  return new Date(duration * 1000).toTimeString().split(" ")[0];
}

function updateSeekTimes(input) {
  const percent = parseFloat(input.value) / 100;
  const duration = parseFloat(input.dataset.duration);

  const before = duration * percent;

  const [tb, ta] = getTimeElms();
  tb.innerText = durationToStr(before);
  ta.innerText = durationToStr(duration - before);
}
