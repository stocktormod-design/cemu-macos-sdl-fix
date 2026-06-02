/* Dump SDL_GameController mapping lines for all connected gamepads (macOS/Linux). */
#include <SDL.h>
#include <stdio.h>

int main(void) {
	if (SDL_Init(SDL_INIT_GAMECONTROLLER | SDL_INIT_JOYSTICK) != 0)
		return 1;

	const int n = SDL_NumJoysticks();
	for (int i = 0; i < n; ++i) {
		if (!SDL_IsGameController(i))
			continue;
		SDL_GameController *gc = SDL_GameControllerOpen(i);
		if (!gc)
			continue;
		char *mapping = SDL_GameControllerMapping(gc);
		if (mapping) {
			puts(mapping);
			SDL_free(mapping);
		}
		SDL_GameControllerClose(gc);
	}

	SDL_Quit();
	return 0;
}
