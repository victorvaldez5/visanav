import {computed, ref} from "vue";
import {defineStore} from "pinia";
import {authService} from "@/services/authService";
import {locationService} from '@/services/locationService';
import {toast} from "vue-sonner";
import {useRouter} from "vue-router";


interface ListItem {
    id: number;
    name: string;
    code: string;
}

interface Country {
    id: number;
    country_code: string;
    name: string;
}

interface Profile {
    id: number;
    first_name: string;
    middle_name: string;
    last_name: string;
    postal_code: string;
    email: string;
    phone_number: string;
    country: Country;
    subdivision: ListItem;
    preferred_language: ListItem;
    notify_marketing: boolean;
    notify_system: boolean;
}

export const useProfileStore = defineStore("profile", () => {
    // State
    const user = ref<any | null>(null);
    const profile = ref<Profile | null>(null);
    const loading = ref(false);
    const error = ref<string | null>(null);

    const countries = ref<Country[]>([]);
    const subdivisions = ref<ListItem[]>([]);
    const languages = ref<ListItem[]>([]);

    const router = useRouter();

    // Getters
    const hasData = computed(() => !!user.value || !!profile.value);

    // Actions
    async function loadByUserId(userId: number | null) {
        loading.value = true;
        error.value = null;

        if (userId === null) {
            await router.push({name: "Home"});
        }

        try {
            const [_user, _profile, _countries, _languages] = await Promise.all([
                authService.getUser(userId!),
                authService.getProfile(userId!),
                locationService.getCountries(),
                locationService.getLanguages(),
            ]);
            user.value = _user;
            profile.value = _profile;
            countries.value = _countries;
            languages.value = _languages;
        } catch (e: any) {
            error.value = e?.message ?? "Failed to load user/profile";
            toast.error("Failed to load user/profile");
        } finally {
            loading.value = false;
        }
    }

    function getLanguageById(languageCode: string | undefined | ListItem): ListItem | undefined {
        if (!languageCode) return;
        return languages.value.find(language => language.code === languageCode);
    }

    function getCountryById(countryCode: Country | string | undefined): Country | undefined {
        if (!countryCode) return;
        return countries.value.find(country => country.country_code === countryCode);
    }

    function getSubdivisionById(subdivisionCode: string | undefined | ListItem): ListItem | undefined {
        if (!subdivisionCode) return;
        return subdivisions.value.find(subdivision => subdivision.code === subdivisionCode)
    }

    async function updateUser(userId: number, data: any) {
        const updated = await authService.updateUser(userId, data);
        user.value = updated;
        return updated;
    }

    async function updateProfile(userId: number, data: any): Promise<Profile> {
        const payload = {
            ...data,
            country: data.country?.id,
            subdivision: data.subdivision?.id,
            preferred_language: data.preferred_language?.code ?? null,
        }
        const updated = await authService.updateProfile(userId, payload);
        profile.value = updated;
        return updated;
    }

    async function deleteUser(userId: number) {
        await authService.deleteUser(userId);
        reset();
    }

    async function loadSubdivisions(countryCode: string | undefined): Promise<ListItem[]> {
        if (!countryCode) return [];
        const data = await locationService.getSubdivisions(countryCode);
        subdivisions.value = data
        return data
    }

    function reset() {
        user.value = null;
        profile.value = null;
        loading.value = false;
        error.value = null;
    }

    return {
        // state
        user,
        profile,
        loading,
        countries,
        subdivisions,
        languages,
        error,
        // getters
        hasData,
        // actions
        loadByUserId,
        updateUser,
        updateProfile,

        loadSubdivisions,
        deleteUser,
        // helpers
        getCountryById,
        getSubdivisionById,
        getLanguageById,
        reset,
    };
});
